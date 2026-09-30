.PHONY: build clean

build:
	./scripts/01_build_opus.sh

clean:
	rm -rf opus build/opus
