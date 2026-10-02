/* decode_raw.c — [u32 len][bytes]... -> raw PCM (48k mono s16le) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <opus/opus.h>

#define SAMPLE_RATE 48000
#define CHANNELS    1
#define MAX_FRAME   5760  /* 120 ms at 48 kHz, Opus max */

static void die(const char *msg) {
    fprintf(stderr, "decode_raw: %s\n", msg);
    exit(1);
}

static int read_u32le(FILE *f, uint32_t *out) {
    unsigned char b[4];
    size_t n = fread(b, 1, 4, f);
    if (n == 0) return 0;       /* EOF at a clean boundary */
    if (n != 4) die("truncated length field");
    *out = (uint32_t)b[0] | ((uint32_t)b[1]<<8) | ((uint32_t)b[2]<<16) | ((uint32_t)b[3]<<24);
    return 1;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s <in.opusraw> <out.raw>\n", argv[0]);
        return 2;
    }
    const char *in_path  = argv[1];
    const char *out_path = argv[2];

    int err = OPUS_OK;
    OpusDecoder *dec = opus_decoder_create(SAMPLE_RATE, CHANNELS, &err);
    if (err != OPUS_OK) die(opus_strerror(err));

    FILE *fin  = fopen(in_path, "rb");
    if (!fin)  die("cannot open input");
    FILE *fout = fopen(out_path, "wb");
    if (!fout) die("cannot open output");

    unsigned char pkt[1500];
    opus_int16 pcm[MAX_FRAME * CHANNELS];

    unsigned long long frame_count = 0;
    unsigned long long sample_count = 0;

    for (;;) {
        uint32_t len = 0;
        if (!read_u32le(fin, &len)) break;
        if (len > sizeof(pkt)) die("packet too large");

        if (fread(pkt, 1, len, fin) != len) die("truncated packet");

        int n = opus_decode(dec, pkt, (opus_int32)len, pcm, MAX_FRAME, 0);
        if (n < 0) die(opus_strerror(n));

        if (fwrite(pcm, sizeof(opus_int16) * CHANNELS, n, fout) != (size_t)n)
            die("short write");

        frame_count++;
        sample_count += n;
    }

    fprintf(stderr, "decode_raw: %llu frames, %llu samples (%.3f s)\n",
            frame_count, sample_count, (double)sample_count / SAMPLE_RATE);

    fclose(fin);
    fclose(fout);
    opus_decoder_destroy(dec);
    return 0;
}