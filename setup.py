from setuptools import setup, find_packages

setup(
    name="eigenlayer-ai-agent",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "web3>=6.0.0",
        "requests>=2.25.0",
        "python-dotenv>=0.15.0",
        "click>=8.0.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "openai": ["openai>=1.0.0"],
        "anthropic": ["anthropic>=0.5.0"],
        "all": ["openai>=1.0.0", "anthropic>=0.5.0"],
    },
    entry_points={
        "console_scripts": [
            "eigenlayer-agent=eigenlayer_agent.cli:main",
        ],
    },
    python_requires=">=3.10",
    author="Vista Labs",
    description="AI Agent with EigenLayer integration",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/vistalabs-org/eigenlayer-ai-agent",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)