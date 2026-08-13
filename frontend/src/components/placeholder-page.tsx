import { Card,PageHeader } from "@/components/ui";
export function PlaceholderPage({title}:{title:string}){return <><PageHeader title={title}/><Card><p className="text-sm text-slate-600">This navigation area is part of the application foundation. Its feature-specific interface will be implemented in a later frontend phase.</p></Card></>}
