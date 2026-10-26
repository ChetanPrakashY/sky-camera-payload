"""Camera and scene model shared by the simulator and the calibration scripts.

Sensor numbers follow the Sony IMX477 used in the Raspberry Pi HQ Camera (1.55 um pixels, 12-bit
output); gain, noise and dark current are assumed values, marked TBC in the design document until the
real camera is characterised. Only a 512 x 512 window of the sensor is simulated.
"""
import numpy as np

W = H = 512
PIXEL_UM = 1.55
FOCAL_MM = 50.0
PLATE_SCALE = 206265 * PIXEL_UM * 1e-6 / (FOCAL_MM * 1e-3)      # arcsec per pixel
GAIN_E_PER_DN = 0.9          # TBC
READ_NOISE_E = 3.0           # TBC
DARK_E_PER_S = 2.0           # TBC, at the expected operating temperature
FULL_WELL_E = 3500.0         # TBC
OFFSET_DN = 256              # black level
BITS = 12


class Sensor:
    """Fixed per-pixel properties: they are the same in every frame, so calibration can measure them."""

    def __init__(self, seed=1):
        rng = np.random.default_rng(seed)
        y, x = np.mgrid[:H, :W]
        r2 = ((x - W / 2) ** 2 + (y - H / 2) ** 2) / (W / 2) ** 2
        self.vignetting = 1 - 0.25 * r2
        self.prnu = 1 + 0.01 * rng.standard_normal((H, W))
        self.dark_scale = 1 + 0.1 * rng.standard_normal((H, W))
        self.hot = rng.random((H, W)) < 5e-4
        self.dead = rng.random((H, W)) < 2e-4
        self.dark_scale[self.hot] = 200.0
        self.rng = rng

    def expose(self, electrons_per_s, t_exp):
        """One raw frame in DN from a scene given as electrons per second per pixel (before optics losses)."""
        rng = self.rng
        sig = electrons_per_s * self.vignetting * self.prnu * t_exp
        sig[self.dead] = 0.0
        e = rng.poisson(sig + DARK_E_PER_S * self.dark_scale * t_exp).astype(float)
        e = np.minimum(e, FULL_WELL_E) + READ_NOISE_E * rng.standard_normal((H, W))
        dn = np.round(e / GAIN_E_PER_DN + OFFSET_DN)
        return np.clip(dn, 0, 2 ** BITS - 1).astype(np.uint16)


def star_field(rng, n_stars=60, sky_e_per_s=20.0, psf_sigma_px=1.2):
    """Background sky plus Gaussian stars. Returns the scene (e-/s/px) and a truth table."""
    y, x = np.mgrid[:H, :W]
    scene = np.full((H, W), sky_e_per_s)
    xs, ys = rng.uniform(15, W - 15, n_stars), rng.uniform(15, H - 15, n_stars)
    flux = 10 ** rng.uniform(3.0, 5.0, n_stars)           # total e-/s, spread over ~2 decades
    for xi, yi, f in zip(xs, ys, flux):
        scene += f / (2 * np.pi * psf_sigma_px ** 2) * np.exp(-((x - xi) ** 2 + (y - yi) ** 2) / (2 * psf_sigma_px ** 2))
    return scene, [dict(kind="star", x=a, y=b, flux_e_s=c) for a, b, c in zip(xs, ys, flux)]


def add_streak(scene, x0, y0, angle_deg, length_px, flux_e_s, psf_sigma_px=1.2):
    """A satellite crossing the field during the exposure: a line of the PSF, total flux spread along it."""
    y, x = np.mgrid[:H, :W]
    a = np.deg2rad(angle_deg)
    n = int(length_px * 2)
    for s in np.linspace(-0.5, 0.5, n):
        xc, yc = x0 + s * length_px * np.cos(a), y0 + s * length_px * np.sin(a)
        scene += flux_e_s / n / (2 * np.pi * psf_sigma_px ** 2) * np.exp(-((x - xc) ** 2 + (y - yc) ** 2) / (2 * psf_sigma_px ** 2))
    return dict(kind="streak", x=x0, y=y0, angle_deg=angle_deg, length_px=length_px, flux_e_s=flux_e_s)
