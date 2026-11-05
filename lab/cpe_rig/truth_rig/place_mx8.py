# --pre-place hook: the packer drops the BEL attribute of an MX8 cluster, so the clusters are bound here.  An MX8 cluster = the CPE_MX8 cell on the lower
# half (CPE_LT_L) plus three reserved dummies.  The DUT's upper-half dummy is moved to a far away free CPE because the real L2T4 'dut_o1' takes that place.
FIXED = {"dut": "X146Y19", "cpinx": "X145Y19", "cpiny": "X146Y18"}
SUFFIX = {"": "CPE_LT_L", "$upper": "CPE_LT_U", "$ff_upper": "CPE_FF_U", "$ff_lower": "CPE_FF_L"}
for name, loc in FIXED.items():
    for suf, bel in SUFFIX.items():
        if name == "dut" and suf == "$upper":
            ctx.bindBel("X100Y10/CPE_LT_U", ctx.cells[name + suf], STRENGTH_USER)       # parked: unused CPE elsewhere
            continue
        ctx.bindBel("%s/%s" % (loc, bel), ctx.cells[name + suf], STRENGTH_USER)
    print("hook: placed", name, "at", loc)
# dut_o1 is bound by its BEL attribute
