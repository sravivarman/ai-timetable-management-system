"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { MasterDataManager } from "@/components/master-data-manager";
import { EmptyState, LoadingState, PageHeader } from "@/components/ui";
import { resolveMasterConfig } from "@/lib/master-data-config";

export default function MasterDataModulePage() {
  return <Suspense fallback={<LoadingState />}><MasterDataModule /></Suspense>;
}

function MasterDataModule() {
  const params = useParams<{ module: string }>();
  const search = useSearchParams();
  const routeModule = params.module;
  const variant = search.get("variant");
  const config = resolveMasterConfig(routeModule, variant);
  if (!config) return <><PageHeader title="Master data" /><EmptyState title="Unknown master-data module" detail="Choose a module from the Master Data dashboard." /></>;
  return <MasterDataManager config={config} module={routeModule} variant={variant} />;
}
