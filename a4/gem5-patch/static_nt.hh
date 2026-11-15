/*
 * StaticNotTakenBP - MSCS-531 Assignment 4 addition.
 * A static conditional-branch predictor that always predicts NOT TAKEN.
 * It keeps no state and never learns, so it serves as the
 * "without branch prediction" baseline. Unconditional jumps, calls and
 * returns are handled by the BPU's BTB/RAS exactly as with other predictors.
 */
#ifndef __CPU_PRED_STATIC_NT_HH__
#define __CPU_PRED_STATIC_NT_HH__

#include "cpu/pred/conditional.hh"
#include "params/StaticNotTakenBP.hh"

namespace gem5
{
namespace branch_prediction
{

class StaticNotTakenBP : public ConditionalPredictor
{
  public:
    StaticNotTakenBP(const StaticNotTakenBPParams &params)
        : ConditionalPredictor(params)
    {}

    Prediction
    lookup(ThreadID tid, Addr pc, void *&bp_history) override
    {
        return predictWithDefaultLatency(false);
    }

    void branchPlaceholder(ThreadID tid, Addr pc, bool uncond,
                           void *&bp_history) override {}

    void updateHistories(ThreadID tid, Addr pc, bool uncond, bool taken,
                         Addr target, const StaticInstPtr &inst,
                         void *&bp_history) override {}

    void update(ThreadID tid, Addr pc, bool taken, void *&bp_history,
                bool squashed, const StaticInstPtr &inst,
                Addr target) override {}

    void squash(ThreadID tid, void *&bp_history) override {}
};

} // namespace branch_prediction
} // namespace gem5

#endif // __CPU_PRED_STATIC_NT_HH__
