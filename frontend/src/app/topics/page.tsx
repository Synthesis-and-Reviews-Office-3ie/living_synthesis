"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth-context";
import { topicsApi, Topic } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Plus, FileText, MoreVertical, Pencil, Trash2, Pause, Play } from "lucide-react";
import Link from "next/link";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";
import { useMutation, useQueryClient } from "@tanstack/react-query";

export default function TopicsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const { data: topicsData, isLoading } = useQuery({
    queryKey: ["topics"],
    queryFn: async () => {
      const response = await topicsApi.list();
      return response.data as Topic[];
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => topicsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      toast.success("Topic deleted");
    },
    onError: () => {
      toast.error("Failed to delete topic");
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      topicsApi.update(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["topics"] });
      toast.success("Topic updated");
    },
    onError: () => {
      toast.error("Failed to update topic");
    },
  });

  const topics = topicsData || [];

  const tierLimits = {
    free: 1,
    pro: 3,
    team: 10,
  };

  const limit = tierLimits[user?.tier || "free"];
  const canCreateTopic = topics.length < limit;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Topics</h1>
          <p className="text-muted-foreground">
            Manage your research topics and newsletters
          </p>
        </div>
        <Link href="/topics/new">
          <Button disabled={!canCreateTopic}>
            <Plus className="mr-2 h-4 w-4" />
            New Topic
          </Button>
        </Link>
      </div>

      {!canCreateTopic && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="py-4">
            <p className="text-sm text-amber-800">
              You&apos;ve reached your topic limit ({limit} topics).{" "}
              <Link href="/settings" className="font-medium underline">
                Upgrade your plan
              </Link>{" "}
              to create more.
            </p>
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {[1, 2].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader>
                <div className="h-6 bg-muted rounded w-1/2" />
                <div className="h-4 bg-muted rounded w-3/4 mt-2" />
              </CardHeader>
              <CardContent>
                <div className="h-4 bg-muted rounded w-1/4" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : topics.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileText className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="font-semibold text-lg mb-2">No topics yet</h3>
            <p className="text-muted-foreground text-center mb-4">
              Create your first topic to start receiving AI-curated newsletters
            </p>
            <Link href="/topics/new">
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Create Topic
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {topics.map((topic) => (
            <Card key={topic.id} className="relative">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <Link href={`/topics/${topic.id}`}>
                      <CardTitle className="text-lg hover:text-primary transition-colors">
                        {topic.name}
                      </CardTitle>
                    </Link>
                    <div className="flex gap-2 mt-2">
                      <Badge variant={topic.is_active ? "default" : "secondary"}>
                        {topic.is_active ? "Active" : "Paused"}
                      </Badge>
                      <Badge variant="outline">{topic.frequency}</Badge>
                    </div>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem asChild>
                        <Link href={`/topics/${topic.id}/edit`}>
                          <Pencil className="mr-2 h-4 w-4" />
                          Edit
                        </Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() =>
                          toggleMutation.mutate({
                            id: topic.id,
                            is_active: !topic.is_active,
                          })
                        }
                      >
                        {topic.is_active ? (
                          <>
                            <Pause className="mr-2 h-4 w-4" />
                            Pause
                          </>
                        ) : (
                          <>
                            <Play className="mr-2 h-4 w-4" />
                            Resume
                          </>
                        )}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-red-600"
                        onClick={() => {
                          if (confirm("Are you sure you want to delete this topic?")) {
                            deleteMutation.mutate(topic.id);
                          }
                        }}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                {topic.description && (
                  <CardDescription className="mt-2">{topic.description}</CardDescription>
                )}
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                  <span>
                    {topic.last_run_at
                      ? `Last run: ${new Date(topic.last_run_at).toLocaleDateString()}`
                      : "Never run"}
                  </span>
                  <Link
                    href={`/topics/${topic.id}`}
                    className="text-primary hover:underline"
                  >
                    View details →
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
