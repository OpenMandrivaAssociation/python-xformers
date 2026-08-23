%undefine _debugsource_packages

# Space-separated: xformers setup.py splits HIP_ARCHITECTURES on whitespace.
%global hip_archs gfx906 gfx908 gfx90a gfx942 gfx1030 gfx1100 gfx1101 gfx1102 gfx1200 gfx1201
# third_party/composable_kernel_tiled pin from xformers v0.0.35 (.gitmodules).
# The PyPI sdist omits it; cooker has no composable-kernel package.
%global ck_commit 50fad035248b154cdfa4505cf5de7465ce146149

Name:		python-xformers
Version:	0.0.35
Release:	2
Summary:	Hackable transformer building blocks
License:	BSD-3-Clause AND MIT
Group:		Development/Python
URL:		https://github.com/facebookresearch/xformers
Source0:	https://files.pythonhosted.org/packages/source/x/xformers/xformers-%{version}.tar.gz
Source1:	https://github.com/ROCm/composable_kernel/archive/%{ck_commit}.tar.gz#/composable_kernel-%{ck_commit}.tar.gz
# Not Patch0: the python buildsystem autosetup would apply it to Source0.
Source2:	0001-ck-tile-clang23-rdna.patch

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
BuildRequires:	hipcc
BuildRequires:	/usr/bin/clang-offload-bundler
BuildRequires:	cmake(hip)
BuildRequires:	cmake(rocthrust)
BuildRequires:	cmake(rocprim)
BuildRequires:	cmake(hipcub)
Requires:	python%{pyver}dist(torch)
Requires:	python%{pyver}dist(numpy)

%description
xFormers is a collection of optimized transformer components.
HIP flash-attention kernels are compiled when the build-time
python-torch is the ROCm build (torch.version.hip). Radeon works
on x86_64 and aarch64.

%prep -a
# setup.py only enables HIP if torch.version.hip is set. Also honour
# HIP_ARCHITECTURES so a ROCm toolchain can be selected explicitly.
sed -i 's/torch.version.hip$/torch.version.hip or os.getenv("HIP_ARCHITECTURES")/' setup.py
# torch 2.13 AutogradState.h uses C++20 bit-field default initializers;
# hipcc -Werror turns the c++17 diagnostic into a hard error.
sed -i 's/-std=c++17/-std=c++20/g' setup.py
# clang 23 is stricter than the -Werror HIP flags xformers ships.
sed -i '/"-Werror",/d' setup.py
# Restore the CK Tile tree setup.py expects (PyPI sdist ships only cutlass).
tar xf %{SOURCE1}
rm -rf third_party/composable_kernel_tiled
mv composable_kernel-%{ck_commit} third_party/composable_kernel_tiled
# clang 23 rejects __host__/__device__ on deduction guides; RDNA wave32
# + headdim 256 divided by zero in the June 2025 FMHA bwd policy.
pushd third_party/composable_kernel_tiled
patch -p1 < %{SOURCE2}
popd

%build -p
export CC=clang
export CXX=clang++
export FORCE_CUDA=0
export BUILD_VERSION=%{version}
export TORCH_CUDA_ARCH_LIST=
export ROCM_PATH=%{_prefix}
export ROCM_HOME=%{_prefix}
export HIP_CLANG_PATH=%{_bindir}
export HIP_DEVICE_LIB_PATH=%{_libdir}/amdgcn/bitcode
export PYTORCH_ROCM_ARCH='gfx906;gfx908;gfx90a;gfx942;gfx1030;gfx1100;gfx1101;gfx1102;gfx1200;gfx1201'
export HIP_ARCHITECTURES='%{hip_archs}'
export XFORMERS_CK_FLASH_ATTN=1
# One hipcc TU already offloads 10 gfx*; ninja -j$nproc OOMs the builder.
export MAX_JOBS=1

%files
%doc README.md
%license LICENSE
%{python_sitearch}/xformers
%{python_sitearch}/xformers-*.*-info
