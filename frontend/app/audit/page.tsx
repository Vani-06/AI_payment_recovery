import { PageHeader, Placeholder } from "@/components/ui";

export default function AuditPage() {
  return (
    <div>
      <PageHeader title="Audit Trail" subtitle="Append-only log, filterable by event, stage, actor and outcome." />
      <Placeholder phase="6" />
    </div>
  );
}
