"""Setup for EPB integration."""

from setuptools import setup

# Read README.md for the long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ha-epb",
    version="1.0.5",
    description="Home Assistant integration for EPB (Electric Power Board)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Aaron Sachs",
    author_email="asachs01@users.noreply.github.com",
    url="https://github.com/asachs01/ha-epb",
    packages=["custom_components.epb"],
    package_data={"custom_components.epb": ["manifest.json", "translations/*.json"]},
    install_requires=[
        "aiohttp>=3.8.0",
        "attrs>=21.0.0",
        "multidict>=4.0.0",
        "yarl>=1.0.0",
        "frozenlist>=1.0.0",
        "typing-extensions>=4.0.0",  # For Python 3.9 compatibility
    ],
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords=["home-assistant", "homeassistant", "epb", "energy", "utility"],
)
