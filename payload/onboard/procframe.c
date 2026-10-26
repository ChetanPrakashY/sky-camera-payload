/* procframe: on-board processing of one sky frame.
 *
 *   procframe CALIBDIR RAW WIDTH HEIGHT INDEX TIME_GPS PACKETS [--csv FILE] [--corrected FILE]
 *
 * 1. dark / flat correction, bad pixels replaced by the median of good neighbours
 * 2. background and noise from the median and MAD of a pixel sample
 * 3. pixels above background + 5 sigma grouped into 8-connected sources
 * 4. per source: flux, centroid, second moments -> elongation, angle, length; streak if elongated
 * 5. one telemetry packet appended to PACKETS (format in docs/src/ICD.md), plus optional CSV
 */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define K_SIGMA 5.0
#define MIN_PIX 4
#define MAX_DET 200
#define STREAK_ELONGATION 3.0
#define ASM_WORD 0x1ACFFC1Du   /* CCSDS attached sync marker */

typedef struct {
    double flux, x, y, angle_deg, length, elong;
    int npix, flags;
} Det;

enum { F_STREAK = 1, F_EDGE = 2, F_SATURATED = 4 };

static void *read_file(const char *path, size_t bytes) {
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); exit(2); }
    void *buf = malloc(bytes);
    if (!buf || fread(buf, 1, bytes, f) != bytes) { fprintf(stderr, "%s: short read\n", path); exit(2); }
    fclose(f);
    return buf;
}

static int cmp_float(const void *a, const void *b) {
    float x = *(const float *)a, y = *(const float *)b;
    return (x > y) - (x < y);
}

static int cmp_det(const void *a, const void *b) {            /* brightest first */
    double x = ((const Det *)a)->flux, y = ((const Det *)b)->flux;
    return (x < y) - (x > y);
}

static uint16_t crc16_ccitt(const uint8_t *p, size_t n) {    /* CRC-16/CCITT-FALSE */
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < n; i++) {
        crc ^= (uint16_t)(p[i] << 8);
        for (int b = 0; b < 8; b++) crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
    return crc;
}

static uint8_t *put(uint8_t *p, uint32_t v, int bytes) {     /* big-endian */
    for (int i = bytes - 1; i >= 0; i--) *p++ = (uint8_t)(v >> (8 * i));
    return p;
}

int main(int argc, char **argv) {
    if (argc < 8) {
        fprintf(stderr, "usage: procframe CALIBDIR RAW WIDTH HEIGHT INDEX TIME_GPS PACKETS [--csv F] [--corrected F]\n");
        return 1;
    }
    const char *cal = argv[1], *rawpath = argv[2], *pktpath = argv[7], *csvpath = NULL, *corrpath = NULL;
    int w = atoi(argv[3]), h = atoi(argv[4]);
    uint32_t index = (uint32_t)strtoul(argv[5], NULL, 10);
    double tgps = atof(argv[6]);
    for (int i = 8; i + 1 < argc; i += 2) {
        if (!strcmp(argv[i], "--csv")) csvpath = argv[i + 1];
        else if (!strcmp(argv[i], "--corrected")) corrpath = argv[i + 1];
    }
    size_t n = (size_t)w * h;
    char path[1024];
    uint16_t *raw = read_file(rawpath, n * 2);
    snprintf(path, sizeof path, "%s/dark.f32", cal);  float *dark = read_file(path, n * 4);
    snprintf(path, sizeof path, "%s/flat.f32", cal);  float *flat = read_file(path, n * 4);
    snprintf(path, sizeof path, "%s/badpix.u8", cal); uint8_t *bad = read_file(path, n);

    /* 1. correction. Files are little-endian, as is the on-board computer (ARM and x86 both are). */
    float *img = malloc(n * sizeof *img);
    uint8_t *sat = calloc(n, 1);
    if (!img || !sat) return 2;
    for (size_t i = 0; i < n; i++) {
        img[i] = ((float)raw[i] - dark[i]) / flat[i];
        sat[i] = raw[i] >= 4095;
    }
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            if (!bad[y * w + x]) continue;
            float v[8]; int k = 0;
            for (int dy = -1; dy <= 1; dy++)
                for (int dx = -1; dx <= 1; dx++) {
                    int xx = x + dx, yy = y + dy;
                    if ((dx || dy) && xx >= 0 && yy >= 0 && xx < w && yy < h && !bad[yy * w + xx]) v[k++] = img[yy * w + xx];
                }
            if (k) { qsort(v, (size_t)k, sizeof *v, cmp_float); img[y * w + x] = (k % 2) ? v[k / 2] : 0.5f * (v[k / 2 - 1] + v[k / 2]); }
        }
    if (corrpath) { FILE *f = fopen(corrpath, "wb"); if (!f || fwrite(img, 4, n, f) != n) return 2; fclose(f); }

    /* 2. background: median and MAD of every 7th pixel (enough samples, much faster than sorting all) */
    size_t ns = n / 7;
    float *s = malloc(ns * sizeof *s);
    if (!s) return 2;
    for (size_t i = 0; i < ns; i++) s[i] = img[i * 7];
    qsort(s, ns, sizeof *s, cmp_float);
    float bg = s[ns / 2];
    for (size_t i = 0; i < ns; i++) s[i] = fabsf(img[i * 7] - bg);
    qsort(s, ns, sizeof *s, cmp_float);
    float sigma = 1.4826f * s[ns / 2];
    float thr = bg + (float)K_SIGMA * sigma;

    /* 3-4. connected components with an explicit stack (no recursion: the stack size is bounded) */
    int32_t *label = calloc(n, sizeof *label), *stack = malloc(n * sizeof *stack);
    Det *det = malloc(MAX_DET * 4 * sizeof *det);
    if (!label || !stack || !det) return 2;
    int ndet = 0, nlab = 0;
    for (size_t start = 0; start < n; start++) {
        if (img[start] <= thr || label[start]) continue;
        nlab++;
        int top = 0; stack[top++] = (int32_t)start; label[start] = nlab;
        double sw = 0, sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0; int np = 0, flags = 0;
        while (top) {
            int32_t i = stack[--top];
            int x = i % w, y = i / w;
            double v = img[i] - bg;
            sw += v; sx += v * x; sy += v * y; sxx += v * x * x; syy += v * y * y; sxy += v * x * y; np++;
            if (x == 0 || y == 0 || x == w - 1 || y == h - 1) flags |= F_EDGE;
            if (sat[i]) flags |= F_SATURATED;
            for (int dy = -1; dy <= 1; dy++)
                for (int dx = -1; dx <= 1; dx++) {
                    int xx = x + dx, yy = y + dy;
                    if (xx < 0 || yy < 0 || xx >= w || yy >= h) continue;
                    int32_t j = yy * w + xx;
                    if (!label[j] && img[j] > thr) { label[j] = nlab; stack[top++] = j; }
                }
        }
        if (np < MIN_PIX || ndet >= MAX_DET * 4) continue;
        Det d = {0};
        d.flux = sw; d.x = sx / sw; d.y = sy / sw; d.npix = np; d.flags = flags;
        double mxx = sxx / sw - d.x * d.x, myy = syy / sw - d.y * d.y, mxy = sxy / sw - d.x * d.y;
        double tr = mxx + myy, disc = sqrt(fmax(0.0, (mxx - myy) * (mxx - myy) / 4 + mxy * mxy));
        double l1 = tr / 2 + disc, l2 = fmax(tr / 2 - disc, 1e-6);
        d.elong = sqrt(l1 / l2);
        d.angle_deg = 0.5 * atan2(2 * mxy, mxx - myy) * 180.0 / M_PI;
        if (d.angle_deg < 0) d.angle_deg += 180.0;
        d.length = sqrt(12.0 * l1);                     /* a uniform line of length L has variance L^2/12 */
        if (d.elong > STREAK_ELONGATION) d.flags |= F_STREAK;
        det[ndet++] = d;
    }
    qsort(det, (size_t)ndet, sizeof *det, cmp_det);
    if (ndet > MAX_DET) ndet = MAX_DET;

    /* 5. telemetry packet: ASM | version | index | gps s | gps us | n | n x 16-byte detections | CRC */
    size_t len = 4 + 1 + 4 + 4 + 4 + 2 + 16 * (size_t)ndet + 2;
    uint8_t *pkt = malloc(len), *p = pkt;
    if (!pkt) return 2;
    uint32_t sec = (uint32_t)tgps, usec = (uint32_t)llround((tgps - sec) * 1e6);
    p = put(p, ASM_WORD, 4); p = put(p, 1, 1); p = put(p, index, 4); p = put(p, sec, 4); p = put(p, usec, 4);
    p = put(p, (uint32_t)ndet, 2);
    for (int k = 0; k < ndet; k++) {
        Det *d = &det[k];
        p = put(p, (uint32_t)lround(d->x * 32), 2);   /* 1/32 pixel resolution */
        p = put(p, (uint32_t)lround(d->y * 32), 2);
        p = put(p, (uint32_t)lround(fmin(d->flux, 4.0e9)), 4);
        p = put(p, (uint32_t)(int16_t)lround(d->angle_deg * 100), 2);
        p = put(p, (uint32_t)lround(fmin(d->length * 10, 65535)), 2);
        p = put(p, (uint32_t)(d->npix > 65535 ? 65535 : d->npix), 2);
        p = put(p, (uint32_t)d->flags, 1);
        p = put(p, 0, 1);
    }
    p = put(p, crc16_ccitt(pkt + 4, (size_t)(p - pkt) - 4), 2);
    FILE *f = fopen(pktpath, "ab");
    if (!f || fwrite(pkt, 1, len, f) != len) { perror(pktpath); return 2; }
    fclose(f);
    if (csvpath) {
        FILE *c = fopen(csvpath, "w");
        if (!c) { perror(csvpath); return 2; }
        fprintf(c, "x,y,flux_dn,npix,elongation,angle_deg,length_px,flags\n");
        for (int k = 0; k < ndet; k++)
            fprintf(c, "%.3f,%.3f,%.1f,%d,%.2f,%.2f,%.1f,%d\n", det[k].x, det[k].y, det[k].flux, det[k].npix,
                    det[k].elong, det[k].angle_deg, det[k].length, det[k].flags);
        fclose(c);
    }
    printf("frame %u: background %.1f DN, noise %.2f DN, %d sources, packet %zu bytes\n", index, bg, sigma, ndet, len);
    free(raw); free(dark); free(flat); free(bad); free(img); free(sat); free(s); free(label); free(stack); free(det); free(pkt);
    return 0;
}
