from setuptools import setup, find_packages

setup(
    name="ai_erpnext",
    version="0.0.1",
    description="AI-powered document processing for ERPNext",
    author="Nikhil",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=["anthropic", "pymupdf", "Pillow"]
)