setup: requirements.txt
	pip install -r requirements.txt
clean:
	rm -rf __pycache__
	rm -rf src/aiocasambi.egg-info
	rm -rf dist/*
	rm -rf src/aiocasambi/__pycache__
build:
	python3 setup.py sdist bdist_wheel
upload: clean build
	python3 setup.py sdist bdist_wheel; twine upload dist/*
.PHONY: build clean upload renovate renovate-summary

renovate:
	@./bin/renovate/run.sh

renovate-summary:
	@./bin/renovate/run.sh --summary