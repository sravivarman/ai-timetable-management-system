"use client";
import { useEffect } from "react";
import { useAuth } from "@/providers/auth-provider";
import { LoadingState } from "@/components/ui";
export default function LogoutPage(){const{logout}=useAuth();useEffect(()=>{void logout()},[logout]);return <main className="mx-auto max-w-md p-10"><LoadingState label="Signing out" /></main>}
