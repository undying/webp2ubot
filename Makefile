
SHELL := /bin/bash
DOCKER_IMAGE := webp2u

app:
	python ./app/main.py

docker: docker_build
	source .env \
		&& env \
		&& docker run \
			--rm -it \
			--env-file .env \
			$(DOCKER_IMAGE)

docker_build:
	docker build -t $(DOCKER_IMAGE) .

