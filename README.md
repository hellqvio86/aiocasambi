![PyPI - Python Version](https://img.shields.io/pypi/pyversions/aiocasambi) ![PyPI](https://img.shields.io/pypi/v/aiocasambi) ![GitHub](https://img.shields.io/github/license/hellqvio86/aiocasambi) ![GitHub issues](https://img.shields.io/github/issues-raw/hellqvio86/aiocasambi) ![GitHub last commit](https://img.shields.io/github/last-commit/hellqvio86/aiocasambi) ![PyPI - Downloads](https://img.shields.io/pypi/dm/aiocasambi)

# Python library for controlling Casambi lights

aio Python library for controlling Casambi via Cloud API

## Supported modes

These modes are implemented:

- on/off
- brightness
- color temperature
- rgb
- rgbw

## Getting Started

1. Request developer api key from Casambi: https://developer.casambi.com/
2. Setup a site in Casambi app: http://support.casambi.com/support/solutions/articles/12000041325-how-to-create-a-site

## Installating

Install this library through pip:

```
pip install aiocasambi
```

## Authors

- **Olof Hellqvist** - _Initial work_

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

### Test script

Add the credentials to _casambi.yaml.example_ and rename the file to _casambi.yaml_

#### Build localy in env

```
python3 -m venv aiocasambi
source ./aiocasambi/bin/activate
./aiocasambi/bin/pip3 install -r ./aiocasambi/requirements.txt
```

## Disclaimer

This library is neither affiliated with nor endorsed by Casambi.
