import { useStore } from "../../state/store";
import { useScenario } from "../../state/scenario";
import CountySummary from "./CountySummary";
import ShelterDetails from "./ShelterDetails";
import CouldNotTell from "./CouldNotTell";
import AffectedSummary from "../scenario/AffectedSummary";
import ReceivingList from "../scenario/ReceivingList";

/**
 * The Details tab: county/shelter summaries, the hurricane lists and "What we could not tell you".
 * SidePanel owns the tab; hovering, selecting or drawing never switches to it (feature 003 FR-012).
 */
export default function DetailsPanel() {
  const { state } = useStore();
  const scenario = useScenario();
  return (
    <div className="details">
      {state.selectedShelterId ? <ShelterDetails /> : <CountySummary />}
      {scenario && (
        <>
          <AffectedSummary />
          <ReceivingList />
        </>
      )}
      <CouldNotTell />
    </div>
  );
}
