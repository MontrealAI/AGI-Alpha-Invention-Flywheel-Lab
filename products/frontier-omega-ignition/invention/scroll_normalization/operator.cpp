#include "vc_reader/src/cpp/transforms/cpu/normalization.hpp"

using namespace vcr::transforms;

template<class Float>
int normalize(Float* data, std::size_t n, const std::uint8_t* valid) noexcept {
    if (!data || !n) return 1;
    try {
        Normalize options;
        options.mode = Normalization::Robust;
        normalization_detail::normalize_order(data, n, options, valid);
        return 0;
    } catch (...) {
        return 1;
    }
}

extern "C" int normalize_float(float* data, std::size_t n, const std::uint8_t* valid) noexcept {
    return normalize(data, n, valid);
}
extern "C" int normalize_double(double* data, std::size_t n, const std::uint8_t* valid) noexcept {
    return normalize(data, n, valid);
}
