#include "plugin/hardware_plugin.hpp"

namespace codegreen {

class ARMPMUAdapter : public HardwarePlugin {
public:
    ARMPMUAdapter() = default;
    ~ARMPMUAdapter() override = default;

    std::string name() const override { return "ARM PMU"; }
    std::unique_ptr<Measurement> get_measurement() const override { return nullptr; }
    bool init() override { return true; }
    void cleanup() override {}
    bool is_available() const override { return false; }
};

} // namespace codegreen
