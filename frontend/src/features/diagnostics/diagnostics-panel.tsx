"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { runDiagnostics, type CheckResult, type CheckStatus } from "@/features/diagnostics/run";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<
  CheckStatus,
  { label: string; icon: typeof XCircle; className: string }
> = {
  pass: { label: "Pass", icon: CheckCircle2, className: "text-emerald-600" },
  warn: { label: "Notice", icon: AlertTriangle, className: "text-amber-600" },
  fail: { label: "Fail", icon: XCircle, className: "text-destructive" },
};

function CheckRow({ result }: { result: CheckResult }) {
  const { icon: Icon, className, label } = STATUS_STYLE[result.status];
  return (
    <li className="flex items-start gap-3 py-3">
      <Icon className={cn("mt-0.5 size-5 shrink-0", className)} aria-label={label} />
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-sm font-medium">{result.label}</p>
        <p className="text-sm break-words text-muted-foreground">{result.detail}</p>
        {result.requestId ? (
          <p className="font-mono text-xs text-muted-foreground">request id {result.requestId}</p>
        ) : null}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1">
        {result.httpStatus ? <Badge variant="outline">HTTP {result.httpStatus}</Badge> : null}
        {result.durationMs !== null ? (
          <span className="text-xs text-muted-foreground tabular-nums">{result.durationMs} ms</span>
        ) : null}
      </div>
    </li>
  );
}

export function DiagnosticsPanel() {
  const { data, isFetching, isError, refetch } = useQuery({
    queryKey: ["diagnostics"],
    queryFn: runDiagnostics,
    staleTime: 0,
    retry: false,
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">API base</p>
            {data ? (
              <p className="text-sm font-medium">{data.apiBaseUrl}</p>
            ) : (
              <Skeleton className="h-5 w-64" />
            )}
          </div>
          <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={cn(isFetching && "animate-spin")} aria-hidden />
            Run again
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          {isError ? (
            <p role="alert" className="text-sm text-destructive">
              The diagnostics could not run.
            </p>
          ) : data ? (
            <ul className="divide-y" aria-label="Diagnostic results">
              {data.results.map((result) => (
                <CheckRow key={result.id} result={result} />
              ))}
            </ul>
          ) : (
            <div className="space-y-3" aria-busy="true">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
