import { useEffect, useState } from 'react';
import { Command } from 'cmdk';
import { useNavigate } from 'react-router-dom';
import {
    LayoutDashboard,
    FileText,
    CheckSquare,
    BarChart3,
    Activity,
    Bot,
    Search,
    Upload,
    Moon
} from 'lucide-react';
import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';

export function CommandPalette() {
    const [open, setOpen] = useState(false);
    const navigate = useNavigate();

    useEffect(() => {
        const down = (e: KeyboardEvent) => {
            if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                setOpen((open) => !open);
            }
        };
        document.addEventListener('keydown', down);
        return () => document.removeEventListener('keydown', down);
    }, []);

    const runCommand = (command: () => void) => {
        setOpen(false);
        command();
    };

    return (
        <>
            {/* Background Overlay */}
            {open && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[9998]" aria-hidden="true" onClick={() => setOpen(false)} />
            )}

            <Command.Dialog
                open={open}
                onOpenChange={setOpen}
                label="Global Command Menu"
                className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[640px] max-w-[90vw] bg-white rounded-xl shadow-2xl border border-gray-200 p-0 z-[9999] overflow-hidden"
            >
                <div className="flex items-center border-b px-4" cmdk-input-wrapper="">
                    <Search className="w-5 h-5 text-gray-400 mr-3" />
                    <Command.Input
                        placeholder="Type a command or search..."
                        className="flex-1 h-14 bg-transparent outline-none text-base text-gray-800 placeholder:text-gray-400"
                    />
                    <div className="flex gap-1">
                        <kbd className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium text-gray-500 bg-gray-100 border border-gray-200 rounded-md shadow-[0_1px_0_0_rgb(0_0_0/0.05)]">
                            ESC
                        </kbd>
                    </div>
                </div>

                <Command.List className="max-h-[300px] overflow-y-auto overflow-x-hidden p-2 scroll-py-2 custom-scrollbar">
                    <Command.Empty className="py-6 text-center text-sm text-gray-500">
                        No results found.
                    </Command.Empty>

                    <Command.Group heading="Navigation" className="mb-2">
                        <div className="px-2 py-1.5 text-xs font-bold text-gray-400 uppercase select-none">App</div>
                        <CommandItem icon={LayoutDashboard} onSelect={() => runCommand(() => navigate('/'))}>
                            Dashboard
                        </CommandItem>
                        <CommandItem icon={FileText} onSelect={() => runCommand(() => navigate('/documents'))}>
                            Documents Inbox
                        </CommandItem>
                        <CommandItem icon={CheckSquare} onSelect={() => runCommand(() => navigate('/approvals'))}>
                            Approvals
                        </CommandItem>
                        <CommandItem icon={BarChart3} onSelect={() => runCommand(() => navigate('/reports'))}>
                            Reports & Ledger
                        </CommandItem>
                        <CommandItem icon={Activity} onSelect={() => runCommand(() => navigate('/evidence'))}>
                            Evidence & Timeline
                        </CommandItem>
                        <CommandItem icon={Bot} onSelect={() => runCommand(() => navigate('/copilot'))}>
                            Copilot Agent
                        </CommandItem>
                    </Command.Group>

                    <Command.Separator className="my-1 h-px bg-gray-100" />

                    <Command.Group heading="Actions" className="mb-2">
                        <div className="px-2 py-1.5 text-xs font-bold text-gray-400 uppercase select-none">Actions</div>
                        <CommandItem icon={Upload} onSelect={() => runCommand(() => navigate('/documents?action=upload'))}>
                            Upload Document
                        </CommandItem>
                        <CommandItem icon={Moon} onSelect={() => runCommand(() => console.log('Dark mode'))}>
                            Toggle Dark Mode
                        </CommandItem>
                    </Command.Group>
                </Command.List>

                <div className="px-4 py-2 border-t bg-gray-50 flex items-center justify-between text-xs text-gray-400">
                    <div className="flex gap-4">
                        <span>Navigate <kbd className="font-sans">↓ ↑</kbd></span>
                        <span>Select <kbd className="font-sans">↵</kbd></span>
                    </div>
                    <span>ProTip: Ask Copilot for complex tasks</span>
                </div>
            </Command.Dialog>
        </>
    );
}

function CommandItem({ children, icon: Icon, onSelect, className }: any) {
    return (
        <Command.Item
            onSelect={onSelect}
            className={twMerge(clsx(
                "flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm text-gray-700 cursor-pointer transition-all duration-150 select-none",
                "hover:bg-gray-100/80 active:bg-gray-200/80",
                "aria-selected:bg-blue-50 aria-selected:text-blue-700 aria-selected:shadow-sm",
                className
            ))}
        >
            {Icon && <Icon className="w-4.5 h-4.5 opacity-70" />}
            <span className="flex-1 truncate font-medium">{children}</span>
        </Command.Item>
    );
}
