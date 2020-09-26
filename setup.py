import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="doxycheck",
    version="0.0.1",
    author="Robert Winkler",
    author_email="robertwinkler147@gmail.com",
    description="Helper utility for checking Doxygen/Sphinx+Breathe documentation",  # noqa: E501
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rw1nkler/doxycheck",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "OSI Approved :: ISC License (ISCL)",
        "Operating System :: OS Independent",
        "Topic :: Documentation",
        "Topic :: Documentation :: Sphinx",
    ],
    python_requires='>=3.6',
    install_requires=[
        'breathe',
        'colorama',
        'doxygen-interface',
        'parse',
        'pprint'
        'sphinx',
        'sphinx_rtd_theme',
    ],
    entry_points={
        "console_scripts": ['doxycheck=doxycheck:main']
    }
)
