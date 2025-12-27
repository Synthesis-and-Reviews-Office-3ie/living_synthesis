"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { topicsApi, Topic } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, FileText, Mail, TrendingUp } from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  const { user } = useAuth();
  
  const { data: topicsData } = useQuery({
    queryKey: ["topics"],
    queryFn: async () => {
      const response = await topicsApi.list();
      return response.data as Topic[];
    },
  });

  const topics = topicsData || [];
  const activeTopics = topics.filter((t) => t.is_active);

  const tierLimits = {
    free: { topics: 1, frequency: ["weekly"] },
    pro: { topics: 3, frequency: ["daily", "weekly"] },
    team: { topics: 10, frequency: ["daily", "weekly"] },
  };

  const limit = tierLimits[user?.tier || "free"];
  const canCreateTopic = topics.length < limit.topics;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">
            Welcome back, {user?.name || user?.email}
          </p>
        </div>
        <Button disabled={!canCreateTopic} asChild>
          <Link href="/topics/new">
            <Plus className="mr-2 h-4 w-4" />
            New Topic
          </Link>
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active Topics</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeTopics.length}</div>
            <p className="text-xs text-muted-foreground">
              of {limit.topics} available
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Newsletters Sent</CardTitle>
            <Mail className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground">this month</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Your Plan</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold capitalize">{user?.tier}</div>
            {user?.tier === "free" && (
              <Link href="/settings" className="text-xs text-primary hover:underline">
                Upgrade to Pro
              </Link>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Topics */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Your Topics</h2>
        {topics.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <FileText className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="font-semibold text-lg mb-2">No topics yet</h3>
              <p className="text-muted-foreground text-center mb-4">
                Create your first topic to start receiving AI-curated newsletters
              </p>
              <Button asChild>
                <Link href="/topics/new">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Topic
                </Link>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {topics.map((topic) => (
              <Link key={topic.id} href={`/topics/${topic.id}`}>
                <Card className="hover:border-primary transition-colors cursor-pointer">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">{topic.name}</CardTitle>
                      <div className="flex gap-2">
                        <Badge variant={topic.is_active ? "default" : "secondary"}>
                          {topic.is_active ? "Active" : "Paused"}
                        </Badge>
                        <Badge variant="outline">{topic.frequency}</Badge>
                      </div>
                    </div>
                    {topic.description && (
                      <CardDescription>{topic.description}</CardDescription>
                    )}
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {topic.last_run_at
                        ? `Last run: ${new Date(topic.last_run_at).toLocaleDateString()}`
                        : "Never run"}
                    </p>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
