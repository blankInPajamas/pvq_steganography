ROOT := $(shell pwd)
OPUS_PREFIX := $(ROOT)/build/opus
OPUS_CFLAGS := -I$(OPUS_PREFIX)/include
OPUS_LIBS   := -L$(OPUS_PREFIX)/lib -lopus -lm
OPUS_LIB    := $(OPUS_PREFIX)/lib/libopus.a

CC      ?= cc
CFLAGS  ?= -O2 -Wall -Wextra -Wpedantic

.PHONY: build tools clean bootstrap verify

build:
	./scripts/01_build_opus.sh

tools: build/encode_raw build/decode_raw

build/encode_raw: scripts/encode_raw.c $(OPUS_LIB)
	@mkdir -p build
	$(CC) $(CFLAGS) $(OPUS_CFLAGS) $< -o $@ $(OPUS_LIBS)

build/decode_raw: scripts/decode_raw.c $(OPUS_LIB)
	@mkdir -p build
	$(CC) $(CFLAGS) $(OPUS_CFLAGS) $< -o $@ $(OPUS_LIBS)

bootstrap:
	./scripts/bootstrap.sh

verify:
	python3 scripts/verify.py

clean:
	rm -rf opus build/opus build/encode_raw build/decode_raw
