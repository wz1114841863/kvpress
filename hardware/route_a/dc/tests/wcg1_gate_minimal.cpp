#include "Vwcg1_gate_minimal.h"
#include "verilated.h"
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  Vwcg1_gate_minimal d;
  const bool bare = argc > 1 && std::strcmp(argv[1], "BARE_AND") == 0;
  const bool merged = argc > 1 && std::strcmp(argv[1], "MERGED_ENABLE") == 0;
  unsigned checks=0, edges=0;
  bool previous_m=false,previous_s=false, previous_root=false, started=false;
  auto check = [&]() {
    const bool rising=!previous_root && d.clock, falling=previous_root && !d.clock;
    d.eval();
    if(started) {
      if((!previous_m && d.member_clock) || (!previous_s && d.suffix_clock)) {
        if(!rising) throw std::runtime_error("unexpected_positive_edge");
        ++edges;
      }
      if((previous_m && !d.member_clock) || (previous_s && !d.suffix_clock)) {
        if(!falling) throw std::runtime_error("truncated_pulse");
        ++edges;
      }
    }
    if(d.member_known && !d.member_equal) throw std::runtime_error("member_capture_mismatch");
    if(d.suffix_known && !d.suffix_equal) throw std::runtime_error("suffix_capture_mismatch");
    previous_m=d.member_clock;previous_s=d.suffix_clock;previous_root=d.clock;started=true;
    ++checks;
  };
  uint64_t random=0x193bca171106ULL;
  auto data = [&]() {
    random ^= random << 13;random ^= random >> 7;random ^= random << 17;
    d.member_payload=random;d.suffix_handle=~random;
    d.member_position=static_cast<uint16_t>(random>>17)&0x7fff;
    d.suffix_prefix=static_cast<uint16_t>(random>>33);
  };
  try {
    d.clock=0;d.reset=1;d.registered_mode=0;
    d.unsafe_bare_and=bare;d.merged_enable=merged;
    d.member_enable=0;d.suffix_enable=0;data();check();
    d.clock=1;check();d.clock=0;check();d.reset=0;check();
    for(unsigned mode=0;mode<2;++mode) {
      // Switch modes only at LOW, after the monitor is reset.
      d.reset=1;check();d.clock=1;check();d.clock=0;check();
      d.registered_mode=mode;d.reset=0;check();
      for(unsigned cycle=0;cycle<512;++cycle) {
        d.member_enable=cycle%5!=0;d.suffix_enable=d.member_enable && cycle%3!=0;
        data();check();
        d.clock=1;check(); // registered_mode changes source data/E through NBA here
        data();check(); // data changes at HIGH must not cause another capture
        d.member_enable=!d.member_enable;check();
        d.suffix_enable=!d.suffix_enable;check();
        d.clock=0;check();
      }
    }
    if(bare || merged) throw std::runtime_error("negative_control_not_detected");
    d.final();
    std::printf("WCG1_VERILATOR_MINIMAL_PASS checks=%u edge_checks=%u modes=2\n",checks,edges);
    return 0;
  } catch(const std::exception& e) {
    std::printf("WCG1_VERILATOR_MINIMAL_FAIL %s checks=%u\n",e.what(),checks);
    return 1;
  }
}
