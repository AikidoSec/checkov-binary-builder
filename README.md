# checkov-binary-builder

This repo will take Checkov code and builds it into standalone libraries that can be packaged into and used by our various onprem scanners.
Checkov also supplies their own pre-built libraries. So, why do we build our own? Because Checkov builds their libraries on recent OS's (ubuntu-latest on GH actions for example).

## How this works

We use GitHub Workflows (see ./github/workflows/build.yml) to checkout the Checkov code. Then we use [PyInstaller](https://pyinstaller.org/en/stable/) to create an executable from this Checkov code. This executable gets added as a release asset upon completion of successful build. 

> PyInstaller is used to package Python code into standalone executable applications for various operating systems. It takes a Python script and generates a single executable file that contains all the necessary dependencies and can be run on computers that do not have Python installed.
