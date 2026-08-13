"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarClock } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { apiErrorMessage } from "@/lib/api-client";

const schema = z.object({ email: z.string().email("Enter a valid institutional email"), password: z.string().min(1,"Password is required") }); type FormData = z.infer<typeof schema>;
export default function LoginPage() { const { login, user, loading } = useAuth(); const router = useRouter(); const [serverError,setServerError]=useState(""); const { register,handleSubmit,formState:{errors,isSubmitting} }=useForm<FormData>({resolver:zodResolver(schema)}); useEffect(()=>{if(!loading&&user)router.replace("/dashboard")},[loading,user,router]); return <main className="grid min-h-screen place-items-center bg-gradient-to-br from-brand-900 via-slate-900 to-brand-700 p-4"><div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl"><div className="mb-7 flex items-center gap-3"><span className="rounded-xl bg-brand-50 p-3 text-brand-700"><CalendarClock /></span><div><h1 className="text-xl font-bold">Welcome back</h1><p className="text-sm text-slate-500">Sign in to manage academic timetables</p></div></div><form className="space-y-5" onSubmit={handleSubmit(async(data)=>{setServerError("");try{await login(data.email,data.password)}catch(error){setServerError(apiErrorMessage(error))}})} noValidate><div><label className="label" htmlFor="email">Email</label><input id="email" autoComplete="username" className="field" {...register("email")} />{errors.email&&<p className="mt-1 text-sm text-red-600">{errors.email.message}</p>}</div><div><label className="label" htmlFor="password">Password</label><input id="password" type="password" autoComplete="current-password" className="field" {...register("password")} />{errors.password&&<p className="mt-1 text-sm text-red-600">{errors.password.message}</p>}</div>{serverError&&<p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{serverError}</p>}<button disabled={isSubmitting} className="button-primary w-full">{isSubmitting?"Signing in…":"Sign in"}</button></form></div></main> }
