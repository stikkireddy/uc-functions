from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="uc-functions",
    author="Sri Tikkireddy",
    author_email="sri.tikkireddy@databricks.com",
    description="Decorator to compile Python functions to Databricks UDFs sql statements and inline all the "
                "dependencies",
    long_description=long_description,
    long_description_content_type="text/markdown",
    package_data={
        'dbtunnel': ['**/*.html'],
    },
    url="https://github.com/stikkireddy/uc-functions",
    packages=find_packages(),
    install_requires=["astor", "databricks-sdk>=0.18.0", "black", "pyflakes"],
    setup_requires=["setuptools_scm"],
    use_scm_version=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)
