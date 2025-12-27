"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { authApi } from "@/lib/api";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Loader2, Check, Crown } from "lucide-react";
import { toast } from "sonner";

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [name, setName] = useState(user?.name || "");
  const [email, setEmail] = useState(user?.email || "");

  const updateMutation = useMutation({
    mutationFn: () => authApi.updateProfile({ name, email }),
    onSuccess: () => {
      refreshUser();
      toast.success("Profile updated");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to update profile");
    },
  });

  const tierInfo = {
    free: {
      name: "Free",
      price: "$0/mo",
      features: ["1 topic", "Weekly digest", "Last 4 newsletters"],
    },
    pro: {
      name: "Pro",
      price: "$29/mo",
      features: ["3 topics", "Daily or weekly", "Full archive", "API access"],
    },
    team: {
      name: "Team",
      price: "$99/mo",
      features: ["10 topics", "Team collaboration", "Custom branding", "Priority support"],
    },
  };

  const currentTier = tierInfo[user?.tier || "free"];

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Manage your account and preferences</p>
      </div>

      {/* Profile */}
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Update your personal information</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              updateMutation.mutate();
            }}
            className="space-y-4"
          >
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </div>
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Save Changes
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Subscription */}
      <Card>
        <CardHeader>
          <CardTitle>Subscription</CardTitle>
          <CardDescription>Manage your subscription and billing</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 rounded-lg border">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">{currentTier.name} Plan</h3>
                <Badge variant="secondary">{currentTier.price}</Badge>
              </div>
              <ul className="mt-2 text-sm text-muted-foreground space-y-1">
                {currentTier.features.map((feature) => (
                  <li key={feature} className="flex items-center gap-2">
                    <Check className="h-3 w-3 text-green-500" />
                    {feature}
                  </li>
                ))}
              </ul>
            </div>
            {user?.tier === "free" && (
              <Button className="gap-2">
                <Crown className="h-4 w-4" />
                Upgrade to Pro
              </Button>
            )}
          </div>

          {user?.tier !== "free" && (
            <Button variant="outline">Manage Billing</Button>
          )}
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="border-red-200">
        <CardHeader>
          <CardTitle className="text-red-600">Danger Zone</CardTitle>
          <CardDescription>Irreversible actions</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Delete Account</p>
              <p className="text-sm text-muted-foreground">
                Permanently delete your account and all data
              </p>
            </div>
            <Button variant="destructive" disabled>
              Delete Account
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
