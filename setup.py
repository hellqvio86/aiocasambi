# from distutils.core import setup
from setuptools import setup, find_packages

# read the contents of README file
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="aiocasambi",
    packages=find_packages("src"),
    package_dir={"": "src"},
    version="0.283",
    license="MIT",
    description="aio library to control Casambi light through cloudapi",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Olof Hellqvist",
    author_email="olof.hellqvist@gmail.com",
    url="https://github.com/hellqvio86/aiocasambi",
    download_url="https://github.com/hellqvio86/aiocasambi/archive/v_01.tar.gz",
    keywords=["casambi", "light"],
    python_requires=">=3.6",
    install_requires=["aiohttp", "pyyaml"],
    extras_require={
        "tests": [
            "pyyaml",
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
    ],
)
