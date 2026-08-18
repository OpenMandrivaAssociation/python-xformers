%undefine _debugsource_packages

Name:		python-xformers
Version:	0.0.35
Release:	1
Summary:	Hackable transformer building blocks
License:	BSD-3-Clause
Group:		Development/Python
URL:		https://github.com/facebookresearch/xformers
Source0:	https://files.pythonhosted.org/packages/source/x/xformers/xformers-%{version}.tar.gz

BuildSystem:	python
BuildRequires:	cmake
BuildRequires:	ninja
BuildRequires:	clang
BuildRequires:	pkgconfig(python)
BuildRequires:	python
BuildRequires:	python%{pyver}dist(pip)
BuildRequires:	python%{pyver}dist(setuptools)
BuildRequires:	python%{pyver}dist(wheel)
BuildRequires:	python%{pyver}dist(torch)
BuildRequires:	python%{pyver}dist(numpy)
Requires:	python%{pyver}dist(torch)
Requires:	python%{pyver}dist(numpy)

%description
xFormers is a collection of optimized transformer components. Built
without CUDA or HIP so the same RPM installs on every arch. Memory-
efficient attention falls back to PyTorch / Triton when a GPU compiler
is present at runtime. A HIP kernel rebuild can follow once python-torch
is the ROCm build at compile time.

%prep -a

%build -p
export CC=clang
export CXX=clang++
export FORCE_CUDA=0
export XFORMERS_CK_FLASH_ATTN=0
export BUILD_VERSION=%{version}
export TORCH_CUDA_ARCH_LIST=

%files
%doc README.md
%license LICENSE
%{python_sitearch}/xformers
%{python_sitearch}/xformers-*.*-info
