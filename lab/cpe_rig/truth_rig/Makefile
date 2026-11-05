all: bitfile.bit
synth.json: top.v
	yosys -ql synth.log -p "synth_gatemate -top top -luttree -nomx8 -json $@" $<
bitfile.txt: synth.json top.sdc pins.ccf place_mx8.py
	nextpnr-himbaechel --pre-place place_mx8.py --vopt no-cpe-cp --vopt lookahead=table --vopt place-delay=table --ignore-loops --json $< --device CCGM1A1 --router router2 --seed 25 --sdc top.sdc -o ccf=pins.ccf -o out=$@ --write pnr.json -o fpga_mode=speed -o time_mode=typical
bitfile.bit: bitfile.txt
	gmpack $< $@ --reconfig
prog: bitfile.bit
	openFPGALoader -c gatemate_pgm bitfile.bit
