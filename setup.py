"""
FacetLab SDK - Setup configuration
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="facetlab",
    version="0.2.0",
    author="FacetLab",
    author_email="support@qyzkdesign.com",
    description="AI-powered pre-launch A/B testing and mockup generation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/qyzk/facetlab-sdk-public",
    project_urls={
        "Documentation": "https://qyzkdesign.com/docs/sdk",
        "Bug Tracker": "https://github.com/qyzk/facetlab-sdk/issues",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Testing",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
            "types-requests>=2.25.0",
        ],
        "images": [
            "Pillow>=9.0.0",
        ],
    },
    keywords=[
        "ab-testing",
        "experimentation",
        "ai",
        "machine-learning",
        "virtual-testing",
        "ux",
        "mockup",
    ],
)
