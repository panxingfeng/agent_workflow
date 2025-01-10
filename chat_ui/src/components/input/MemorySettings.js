import React from 'react';
import { Brain } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
  DialogDescription
} from "../ui/dialog";
import { Button } from "../ui/button";
import { Label } from "../ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";

const MemorySettings = ({ maxMemory, onChangeMemory, messagesLength = 0 }) => {
  const [open, setOpen] = React.useState(false);
  const [tempMemory, setTempMemory] = React.useState(maxMemory.toString());

  const handleSave = () => {
    const value = parseInt(tempMemory, 10);
    if (!isNaN(value) && value > 0) {
      onChangeMemory(value);
    }
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="text-gray-600 hover:bg-gray-100/50 hover:text-gray-900"
        >
          <Brain className="h-4 w-4 mr-2" />
          记忆条数 {messagesLength > maxMemory ? maxMemory : messagesLength}/{maxMemory}
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-md bg-white">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold text-gray-900">
            上下文记忆设置
          </DialogTitle>
          <DialogDescription className="text-sm text-gray-500 mt-1">
            设置对话记忆的条数，较长的上下文可以让AI更好地理解对话历史，但也会消耗更多资源。
          </DialogDescription>
        </DialogHeader>

        <div className="p-4 space-y-4">
          <div className="flex items-center gap-4">
            <Label
              htmlFor="maxMemory"
              className="text-sm font-medium text-gray-900 w-20"
            >
              记忆条数
            </Label>
            <Select
              value={tempMemory}
              onValueChange={setTempMemory}
            >
              <SelectTrigger
                id="maxMemory"
                className="w-32 bg-white border border-gray-200"
              >
                <SelectValue placeholder="选择条数" />
              </SelectTrigger>
              <SelectContent>
                {[4, 8, 10, 16].map(num => (
                  <SelectItem
                    key={num}
                    value={num.toString()}
                    className="cursor-pointer hover:bg-gray-100"
                  >
                    {num} 条
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter className="sm:justify-end gap-2 border-t border-gray-100 pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => setOpen(false)}
            className="bg-white hover:bg-gray-50"
          >
            取消
          </Button>
          <Button
            type="button"
            onClick={handleSave}
            className="bg-blue-600 text-white hover:bg-blue-700"
          >
            保存设置
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default MemorySettings;