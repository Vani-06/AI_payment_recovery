"use client";

import { useMemo } from "react";
import ReactFlow, { Background, Handle, Position, type Edge, type Node } from "reactflow";
import "reactflow/dist/style.css";
import { humanize, inrLakh } from "@/lib/format";
import type { LeakGraph as LeakGraphData } from "@/lib/types";

const ATTR_KINDS = new Set(["issuer", "gateway", "method", "region"]);

const KIND_CLASS: Record<string, string> = {
  issuer: "border-blue-deep/40 bg-blue/15 text-ink",
  gateway: "border-peach-deep/50 bg-peach/20 text-ink",
  method: "border-sage-deep/40 bg-sage/15 text-ink",
  region: "border-sage-deep/40 bg-sage/15 text-ink",
  failure: "border-ink/25 bg-surface text-ink",
  loss: "border-outcome-failed/50 bg-outcome-failed/10 text-outcome-failed",
};

function LeakNode({ data }: { data: { label: string; value: string; kind: string } }) {
  return (
    <div className={`rounded-card border px-3 py-2 text-xs shadow-float-sm ${KIND_CLASS[data.kind] ?? ""}`}>
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div className="font-medium">{data.label}</div>
      <div className="tnum text-[10px] opacity-70">{data.value}</div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { leak: LeakNode };

export function LeakGraph({ graph }: { graph: LeakGraphData }) {
  const { nodes, edges } = useMemo(() => {
    const attrs = graph.nodes.filter((n) => ATTR_KINDS.has(n.kind)).sort((a, b) => b.value - a.value);
    const fails = graph.nodes.filter((n) => n.kind === "failure").sort((a, b) => b.value - a.value);
    const loss = graph.nodes.filter((n) => n.kind === "loss");

    const col = (arr: typeof graph.nodes, x: number, y0 = 0): Node[] =>
      arr.map((n, i) => ({
        id: n.id,
        type: "leak",
        position: { x, y: y0 + i * 64 },
        data: { label: humanize(n.label), value: inrLakh(n.value), kind: n.kind },
        draggable: true,
      }));

    const ns: Node[] = [
      ...col(attrs, 0),
      ...col(fails, 320),
      ...col(loss, 660, Math.max(0, (fails.length - 1) * 32)),
    ];

    const maxR = Math.max(1, ...graph.edges.map((e) => e.rupees));
    const es: Edge[] = graph.edges.map((e, i) => {
      const w = e.rupees / maxR;
      return {
        id: `e${i}`,
        source: e.source,
        target: e.target,
        label: e.label || undefined,
        animated: w > 0.18,
        style: { strokeWidth: 1 + 7 * w, stroke: w > 0.18 ? "#5E9E7E" : "#c8c0af" },
        labelStyle: { fill: "#6B6860", fontSize: 10 },
        labelBgStyle: { fill: "#FBF7F0" },
      };
    });
    return { nodes: ns, edges: es };
  }, [graph]);

  return (
    <div className="h-[560px] overflow-hidden rounded-card border border-surface-sunk bg-surface">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.3}
        proOptions={{ hideAttribution: true }}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background color="#e2dac8" gap={20} />
      </ReactFlow>
    </div>
  );
}
