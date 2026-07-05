import { useCallback } from "react";
import { apiErrorMessage } from "./api";
import { useFeedback } from "./feedback";

export interface ApiActionOptions<T> {
  run: () => Promise<T>;
  successMessage?: string;
  errorMessage: string;
  onSuccess?: (result: T) => void | Promise<void>;
}

export function useApiAction() {
  const feedback = useFeedback();

  return useCallback(
    async <T>({
      run,
      successMessage,
      errorMessage,
      onSuccess,
    }: ApiActionOptions<T>): Promise<T | null> => {
      try {
        const result = await run();
        if (successMessage) feedback.success(successMessage);
        await onSuccess?.(result);
        return result;
      } catch (err) {
        feedback.error(apiErrorMessage(err, errorMessage));
        return null;
      }
    },
    [feedback],
  );
}
