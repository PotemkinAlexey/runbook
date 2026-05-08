from setuptools import find_packages, setup


setup(
    name="runbook",
    version="0.1.0",
    description="Small Airflow-oriented runbook DSL.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    license="MIT",
    package_dir={"": "src"},
    packages=find_packages(where="src", include=["runbook", "runbook.*"]),
    python_requires=">=3.8",
    install_requires=[
        "jinja2>=3.0",
    ],
    extras_require={
        "airflow": ["apache-airflow>=2.0"],
        "aws": ["apache-airflow-providers-amazon"],
        "azure": ["apache-airflow-providers-microsoft-azure"],
        "sftp": ["paramiko>=2.0"],
        "slack": ["slack-sdk>=3.0"],
        "snowflake": ["apache-airflow-providers-snowflake"],
    },
)
