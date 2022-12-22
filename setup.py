from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in electronic_payments/__init__.py
from electronic_payments import __version__ as version

setup(
	name="electronic_payments",
	version=version,
	description="Customized Electronic Payment s Utility",
	author="AgriTheory",
	author_email="support@agritheory.dev",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
