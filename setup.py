from setuptools import setup, find_packages
from pip.req import parse_requirements

install_reqs = parse_requirements('requirements.txt', session=False)

version = '0.9.2'

LONG_DESCRIPTION = """
=======================
Docb
=======================
Document database ORM for Python: Current backends are DynamoDB and Cloudant
"""

setup(
    name='docb',
    version=version,
    description="""Document database ORM for Python: Current backends are DynamoDB and Cloudant
    """,
    long_description=LONG_DESCRIPTION,
    classifiers=[
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Environment :: Web Environment",
    ],
    keywords='dynamodb, cloudant',
    author='Brian Jinwright',
    author_email='opensource@ipoots.com',
    maintainer='Brian Jinwright',
    packages=find_packages(),
    url='https://github.com/capless/docb',
    license='GPLv3',
    install_requires=[str(ir.req) for ir in install_reqs],
    include_package_data=True,
    zip_safe=False,
)
