"use client";
import { ErrorState } from "@/components/ui";
export default function GlobalError({error,reset}:{error:Error;reset:()=>void}){return <main className="mx-auto max-w-3xl p-8"><ErrorState message={error.message||"The page could not be loaded."} retry={reset}/></main>}
