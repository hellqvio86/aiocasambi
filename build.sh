#/bin/bash
echo "Clean dirs"
rm -rf src/aiocasambi.egg-info
rm -rf dist/*

echo "Build"
python3 setup.py sdist bdist_wheel

echo "Upload"
twine upload dist/*