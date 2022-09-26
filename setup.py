from setuptools import setup, find_namespace_packages
import re

URL = 'https://github.com/annotell/annotell-python'

package_name = 'kognic-auth'

with open('README.md') as f:
    LONG_DESCRIPTION = f.read()

# resolve version by opening file. We cannot do import during install
# since the package does not yet exist
with open('kognic/auth/__init__.py', 'r') as fd:
    match = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                      fd.read(), re.MULTILINE)
    version = match.group(1) if match else None

if not version:
    raise RuntimeError('Cannot find version information')

# https://packaging.python.org/guides/packaging-namespace-packages/
packages = find_namespace_packages(include=['kognic.*'])

release_status = "Development Status :: 5 - Production/Stable"

setup(
    name=package_name,
    packages=packages,
    namespace_packages=["kognic"],
    version=version,
    description='Kognic Authentication',
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    author='Kognic',
    author_email='Michel Edkrantz <michel.edkrantz@kognic.com>',
    license='MIT',
    url=URL,
    download_url='%s/tarball/%s' % (URL, version),
    keywords=['API', 'Kognic'],
    install_requires=[
        'authlib>=0.14.1,<1.1'
    ],
    extras_require={
        'requests': [
            'requests>=2.20,<3',
        ],
        'httpx': [
            'httpx>=0.20,<1'
        ],
        'full': [
            'requests>=2.20,<3',
            'httpx>=0.20,<1'
        ]
    },
    python_requires='~=3.6',
    include_package_data=True,
    package_data={
        '': ['*.md', 'LICENSE'],
    },
    classifiers=[
        release_status,
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
    ],
)
