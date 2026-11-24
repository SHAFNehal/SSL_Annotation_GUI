"""Setup script for SSL Annotation Studio."""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="annotation-gui",
    version="1.0.0",
    author="Stochastic Simulation Lab",
    description="SSL Annotation Studio: manual and AI-assisted bounding box annotation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    install_requires=requirements,
    extras_require={"build": ["pyinstaller>=6.0.0"],
                    "ai": ["torch>=2.4,<2.11", "torchvision>=0.19,<0.26", "transformers>=4.50,<5"]},
    package_data={"src": ["icons/*.svg", "icons/*.png"]},
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "annotation-gui=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
