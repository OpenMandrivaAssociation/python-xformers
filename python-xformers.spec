%undefine _debugsource_packages

# Space-separated: xformers setup.py splits HIP_ARCHITECTURES on whitespace.
%global hip_archs gfx906 gfx908 gfx90a gfx942 gfx1030 gfx1100 gfx1101 gfx1102 gfx1200 gfx1201

Name:		python-xformers
Version:	0.0.35
Release:	2
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
%ifarch %{x86_64}
BuildRequires:	hipcc
BuildRequires:	cmake(hip)
%endif
Requires:	python%{pyver}dist(torch)
Requires:	python%{pyver}dist(numpy)

%description
xFormers is a collection of optimized transformer components.
On x86_64 the HIP flash-attention kernels are compiled when
the build-time python-torch is the ROCm build (torch.version.hip).
aarch64 stays on the portable C++ extension.

%prep -a
# setup.py only enables HIP if torch.version.hip is set. Also honour
# HIP_ARCHITECTURES so a ROCm toolchain can be selected explicitly.
sed -i 's/torch.version.hip$/torch.version.hip or os.getenv("HIP_ARCHITECTURES")/' setup.py

%build -p
export CC=clang
export CXX=clang++
export FORCE_CUDA=0
export BUILD_VERSION=%{version}
export TORCH_CUDA_ARCH_LIST=
%ifarch %{x86_64}
export ROCM_PATH=%{_prefix}
export ROCM_HOME=%{_prefix}
export HIP_CLANG_PATH=%{_bindir}
export HIP_DEVICE_LIB_PATH=%{_libdir}/amdgcn/bitcode
export PYTORCH_ROCM_ARCH='gfx906;gfx908;gfx90a;gfx942;gfx1030;gfx1100;gfx1101;gfx1102;gfx1200;gfx1201'
export HIP_ARCHITECTURES='%{hip_archs}'
export XFORMERS_CK_FLASH_ATTN=1
%else
export XFORMERS_CK_FLASH_ATTN=0
%endif

%files
%doc README.md
%license LICENSE
%{python_sitearch}/xformers
%{python_sitearch}/xformers-*.*-info
