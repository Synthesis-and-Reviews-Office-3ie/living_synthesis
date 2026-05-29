"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { authApi } from "@/lib/api";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Check, Crown, Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const [name, setName] = useState(user?.name || "");
  const [email, setEmail] = useState(user?.email || "");
  const [selectedModel, setSelectedModel] = useState(user?.preferred_llm_model || "openai/gpt-4o");

  // Fetch available models for user's tier
  const { data: modelsData, isLoading: modelsLoading } = useQuery({
    queryKey: ["available-models"],
    queryFn: () => authApi.getAvailableModels(),
    enabled: !!user,
  });

  // Update selectedModel when modelsData loads
  useEffect(() => {
    if (modelsData?.current_model) {
      setSelectedModel(modelsData.current_model);
    }
  }, [modelsData]);

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

  const updateModelMutation = useMutation({
    mutationFn: (model: string) => authApi.updateProfile({ preferred_llm_model: model }),
    onSuccess: () => {
      refreshUser();
      toast.success("AI model preference updated");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to update model preference");
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

      {/* AI Model Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5" />
            AI Model
          </CardTitle>
          <CardDescription>
            Choose the AI model for generating your newsletters
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {modelsLoading ? (
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Loading available models...</span>
            </div>
          ) : (
            <>
              <div className="space-y-2">
                <Label htmlFor="model">Preferred Model</Label>
                <Select
                  value={selectedModel}
                  onValueChange={(value) => {
                    setSelectedModel(value);
                    updateModelMutation.mutate(value);
                  }}
                  disabled={updateModelMutation.isPending}
                >
                  <SelectTrigger id="model" className="w-full">
                    <SelectValue placeholder="Select a model" />
                  </SelectTrigger>
                  <SelectContent>
                    {modelsData?.models?.map((model: { id: string; name: string; description: string; tier: string }) => (
                      <SelectItem key={model.id} value={model.id}>
                        <div className="flex items-center gap-2">
                          <span>{model.name}</span>
                          {model.tier !== "free" && (
                            <Badge variant="secondary" className="text-xs">
                              {model.tier.toUpperCase()}
                            </Badge>
                          )}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {modelsData?.models?.find((m: any) => m.id === selectedModel)?.description && (
                <p className="text-sm text-muted-foreground">
                  {modelsData.models.find((m: any) => m.id === selectedModel)?.description}
                </p>
              )}
              {user?.tier === "free" && (
                <div className="flex items-center gap-2 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
                  <Crown className="h-4 w-4 text-amber-600" />
                  <p className="text-sm text-amber-800 dark:text-amber-200">
                    Upgrade to Pro for access to advanced models including Perplexity for research-focused summaries.
                  </p>
                </div>
              )}
            </>
          )}
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
