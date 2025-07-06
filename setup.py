from setuptools import setup, find_packages

setup(
    name='repo2pdf',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'fpdf2',
        'GitPython',
        'inquirer'
    ],
    entry_points={
        'console_scripts': [
            'repo2pdf=repo2pdf.cli:main',
        ],
    },
)
