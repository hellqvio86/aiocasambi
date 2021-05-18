#/bin/bash
echo ""
echo "Clean dirs"
echo ""
rm -rf src/aiocasambi.egg-info
rm -rf dist/*

echo ""
echo "Build"
echo ""
python3 setup.py sdist bdist_wheel

echo ""
echo "Upload"
echo ""
twine upload dist/*