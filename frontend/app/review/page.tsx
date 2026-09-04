import { PageHeader, Placeholder } from "@/components/ui";

export default function ReviewPage() {
  return (
    <div>
      <PageHeader title="Review Queue" subtitle="Actions awaiting human approval in Review mode. Empty in Auto mode." />
      <Placeholder phase="7" />
    </div>
  );
}
