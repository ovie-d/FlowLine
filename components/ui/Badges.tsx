import { InfoTip } from "./InfoTip";

/** Sample crew data must always say so. */
export function SampleChip({ tip = "Crew bases, crew types and equipment are sample data until the operator validates them." }: { tip?: string }) {
  return (
    <InfoTip tip={tip} align="end">
      <span className="whitespace-nowrap rounded border border-warn/60 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-warn">
        Sample — to be validated
      </span>
    </InfoTip>
  );
}

/** Anything simulated (dispatch timeline, moving crew) carries this label. */
export function SimulationBadge() {
  return (
    <InfoTip
      tip="A playback for planning and demos. Only the drive time comes from the router; notification, mobilisation and off-road travel times are not modelled."
      align="end"
    >
      <span className="whitespace-nowrap rounded bg-highlight px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#0B1F3A]">
        Simulation
      </span>
    </InfoTip>
  );
}
