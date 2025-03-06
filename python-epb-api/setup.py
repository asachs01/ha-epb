from setuptools import setup, find_packages

setup(
    name="python-epb-api",
    version="0.1.0",
    description="API client for EPB (Electric Power Board)",
    author="asachs",
    packages=find_packages(),
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
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
) 