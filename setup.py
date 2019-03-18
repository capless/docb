from setuptools import setup, find_packages


def parse_requirements(filename):
    """ load requirements from a pip requirements file """
    lineiter = (line.strip() for line in open(filename))
    return [line for line in lineiter if line and not line.startswith("#")]


version = '1.0.6'

LONG_DESCRIPTION = """
=======================
Docb
=======================
Opinionated Python ORM for DynamoDB
"""

setup(
    name='docb',
    version=version,
    description="""Python ORM for DynamoDB""",
    long_description=LONG_DESCRIPTION,
    classifiers=[
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Environment :: Web Environment",
    ],
    keywords='dynamodb, orm',
    author='Brian Jinwright',
    author_email='opensource@ipoots.com',
    maintainer='Brian Jinwright',
    packages=find_packages(),
    url='https://github.com/capless/docb',
    extras_require={
        'test': parse_requirements('test_requirements.txt'),
    },
    license='GPLv3',
    install_requires=parse_requirements('requirements.txt'),
    include_package_data=True,
    zip_safe=False,
)
