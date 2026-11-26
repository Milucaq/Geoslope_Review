"""Offline terrain preparation; source rasters remain unchanged."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import ColorInterp, Resampling
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gsreview.analytics.john_henry import build_mesh


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def prepare(source, destination, stride=6):
    dem_path, rgb_path = source / 'dem_B_02.tif', source / 'B_02.tif'
    with rasterio.open(dem_path) as dem, rasterio.open(rgb_path) as rgb:
        if dem.crs is None or dem.crs.to_epsg() != 6339 or rgb.crs != dem.crs:
            raise ValueError('CRS incompatibles: se exige EPSG:6339 en ambos rasters')
        if not np.allclose(dem.res, (.3,.3)) or not np.allclose(rgb.res, (.1,.1)):
            raise ValueError('Resoluciones inesperadas')
        if rgb.transform.b != 0 or rgb.transform.d != 0 or rgb.transform.a <= 0 or rgb.transform.e >= 0:
            raise ValueError('Ortofoto no orientada al norte')
        band = dem.read(1, masked=True)
        valid = ~np.ma.getmaskarray(band) & np.isfinite(band.data)
        mesh = build_mesh(band.data, valid, tuple(dem.transform)[:6], stride)
        west, south, east, north = mesh['bounds']
        if (west < rgb.bounds.left or east > rgb.bounds.right or south < rgb.bounds.bottom
                or north > rgb.bounds.top):
            # Small edge discrepancies are handled by boundless reads and explicit mask.
            print('Aviso: parte de la malla supera los límites de la ortofoto.')
        channels = [rgb.colorinterp.index(c)+1 for c in (ColorInterp.red, ColorInterp.green, ColorInterp.blue)]
        if any(rgb.dtypes[c-1] != 'uint8' for c in channels):
            raise ValueError('Se requiere ortofotografía RGB de 8 bits')
        window = from_bounds(west, south, east, north, rgb.transform)
        ratio = (east-west)/(north-south)
        w = max(2, min(2048, round(2048*ratio)))
        h = max(2, min(2048, round(2048/ratio)))
        data = rgb.read(channels, window=window, out_shape=(3,h,w), boundless=True,
                        masked=True, resampling=Resampling.bilinear)
        missing = np.ma.getmaskarray(data).any(axis=0)
        if ColorInterp.alpha in rgb.colorinterp:
            alpha = rgb.read(rgb.colorinterp.index(ColorInterp.alpha)+1, window=window,
                             out_shape=(h,w), boundless=True, resampling=Resampling.nearest)
            missing |= alpha == 0
        pixels = np.moveaxis(data.filled(0),0,-1).copy()
        pixels[missing] = [125,125,125]
        meta = {'site':'John Henry Mine', 'dataset':'OpenTopography OT.112024.6339.2',
                'source_page':'https://portal.opentopography.org/datasetMetadata?otCollectionID=OT.112024.6339.2',
                'license':'CC BY 4.0 (según ficha del conjunto)', 'horizontal_crs':'EPSG:6339',
                'vertical_datum':'NAVD88 (según ficha del conjunto)', 'units':'m',
                'source_dem_resolution_m':list(dem.res),'source_ortho_resolution_m':list(rgb.res),
                'mesh_spacing_m':[stride*dem.res[0],stride*dem.res[1]],
                'native_valid_cells':int(valid.sum()),'native_total_cells':int(valid.size),
                'vertices':len(mesh['positions']),'triangles':len(mesh['indices']),
                'bounds':mesh['bounds'].tolist(),'origin':mesh['origin'].tolist(),
                'elevation_range':mesh['elevation_range'].tolist(), 'texture_size':[w,h],
                'texture_missing_fraction':float(missing.mean()),
                'processing':'Native vertex subsampling, conservative NoData mask, aligned RGB downsampling; no invented elevations.',
                'source_hashes':{p.name:sha(p) for p in (dem_path,rgb_path)}}
    destination.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(destination/'mesh.npz', **mesh)
    Image.fromarray(pixels).save(destination/'texture.jpg', quality=88, optimize=True)
    meta['asset_hashes']={name:sha(destination/name) for name in ('mesh.npz','texture.jpg')}
    (destination/'metadata.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(meta,indent=2,ensure_ascii=False))
    print('Activos generados en',destination)


if __name__ == '__main__':
    prepare(ROOT/'data/terrain_sources/john_henry', ROOT/'assets/terrain/john_henry')
