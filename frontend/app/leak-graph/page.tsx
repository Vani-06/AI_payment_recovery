import { PageHeader, Placeholder } from "@/components/ui";

export default function LeakGraphPage() {
  return (
    <div>
      <PageHeader title="Leak Graph" subtitle="attribute → failure mode → revenue loss, weighted by rupees." />
      <Placeholder phase="7" />
    </div>
  );
}
