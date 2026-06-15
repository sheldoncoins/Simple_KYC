"use client";

import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function AdminLogin({ onSubmit }: { onSubmit: (key: string) => void }) {
  const [key, setKey] = useState("");
  return (
    <Card className="mx-auto mt-16 max-w-sm">
      <CardHeader className="items-center text-center">
        <ShieldCheck className="size-10 text-primary" aria-hidden />
        <CardTitle>Staff sign-in</CardTitle>
        <CardDescription>
          Enter your staff key to access the review console.
        </CardDescription>
      </CardHeader>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (key.trim()) onSubmit(key.trim());
        }}
      >
        <CardContent className="space-y-1.5">
          <Label htmlFor="admin-key">Staff key</Label>
          <Input
            id="admin-key"
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            autoComplete="off"
            required
          />
        </CardContent>
        <CardFooter>
          <Button type="submit" className="w-full" disabled={!key.trim()}>
            Sign in
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
