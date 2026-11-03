import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useHealthQuery() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data, error } = await api.client.GET("/health");
      if (error) {
        throw new Error("后端连接失败");
      }
      return data;
    },
  });
}
