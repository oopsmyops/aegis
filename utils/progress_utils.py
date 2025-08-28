"""
Progress tracking utilities for AEGIS CLI operations.
Provides consistent progress indicators and status updates.
"""

import time
import click
from typing import Optional, List, Dict, Any
from contextlib import contextmanager


class ProgressTracker:
    """Tracks progress for multi-step operations."""
    
    def __init__(self, total_steps: int, operation_name: str = "Operation"):
        self.total_steps = total_steps
        self.current_step = 0
        self.operation_name = operation_name
        self.start_time = time.time()
        self.step_times = []
    
    def start_step(self, step_name: str, step_number: Optional[int] = None) -> None:
        """Start a new step in the operation."""
        if step_number is not None:
            self.current_step = step_number
        else:
            self.current_step += 1
        
        step_start_time = time.time()
        self.step_times.append(step_start_time)
        
        progress_percent = (self.current_step / self.total_steps) * 100
        elapsed_time = step_start_time - self.start_time
        
        click.echo(f"\n{'='*60}")
        click.echo(f"🚀 Step {self.current_step}/{self.total_steps}: {step_name}")
        click.echo(f"📊 Progress: {progress_percent:.0f}%")
        click.echo(f"⏱️  Elapsed: {elapsed_time:.1f}s")
        
        if self.current_step > 1:
            avg_step_time = elapsed_time / (self.current_step - 1)
            remaining_steps = self.total_steps - self.current_step
            estimated_remaining = avg_step_time * remaining_steps
            click.echo(f"🔮 Estimated remaining: {estimated_remaining:.1f}s")
        
        click.echo(f"{'='*60}")
    
    def complete_step(self, success: bool = True, message: Optional[str] = None) -> None:
        """Mark current step as complete."""
        if self.step_times:
            step_duration = time.time() - self.step_times[-1]
            status = "✅" if success else "❌"
            click.echo(f"{status} Step {self.current_step} completed in {step_duration:.1f}s")
            if message:
                click.echo(f"   {message}")
    
    def complete_operation(self, success: bool = True) -> None:
        """Mark entire operation as complete."""
        total_duration = time.time() - self.start_time
        status = "🎉" if success else "💥"
        click.echo(f"\n{status} {self.operation_name} {'completed' if success else 'failed'} in {total_duration:.1f}s")


@contextmanager
def progress_spinner(message: str, success_message: Optional[str] = None, 
                    error_message: Optional[str] = None):
    """Context manager for showing a spinner during operations."""
    import threading
    import itertools
    
    spinner_chars = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
    spinner_running = True
    
    def spin():
        while spinner_running:
            char = next(spinner_chars)
            click.echo(f'\r{char} {message}', nl=False)
            time.sleep(0.1)
    
    spinner_thread = threading.Thread(target=spin)
    
    try:
        spinner_thread.start()
        yield
        spinner_running = False
        spinner_thread.join()
        click.echo(f'\r✅ {success_message or message}')
    except Exception as e:
        spinner_running = False
        spinner_thread.join()
        click.echo(f'\r❌ {error_message or f"{message} failed"}')
        raise


def show_operation_summary(operation: str, stats: Dict[str, Any], 
                          duration: float, success: bool = True) -> None:
    """Show a formatted summary of an operation."""
    status = "✅ Success" if success else "❌ Failed"
    
    click.echo(f"\n{'='*50}")
    click.echo(f"📋 {operation} Summary")
    click.echo(f"{'='*50}")
    click.echo(f"Status: {status}")
    click.echo(f"Duration: {duration:.1f}s")
    
    for key, value in stats.items():
        if isinstance(value, (int, float)):
            click.echo(f"{key}: {value}")
        elif isinstance(value, list):
            click.echo(f"{key}: {len(value)} items")
        else:
            click.echo(f"{key}: {value}")
    
    click.echo(f"{'='*50}")


def show_file_operations(created_files: List[str], modified_files: List[str] = None,
                        deleted_files: List[str] = None) -> None:
    """Show summary of file operations performed."""
    if not any([created_files, modified_files, deleted_files]):
        return
    
    click.echo(f"\n📁 File Operations:")
    
    if created_files:
        click.echo(f"   📝 Created ({len(created_files)}):")
        for file_path in created_files[:5]:  # Show first 5
            click.echo(f"      • {file_path}")
        if len(created_files) > 5:
            click.echo(f"      • ... and {len(created_files) - 5} more")
    
    if modified_files:
        click.echo(f"   ✏️  Modified ({len(modified_files)}):")
        for file_path in modified_files[:3]:  # Show first 3
            click.echo(f"      • {file_path}")
        if len(modified_files) > 3:
            click.echo(f"      • ... and {len(modified_files) - 3} more")
    
    if deleted_files:
        click.echo(f"   🗑️  Deleted ({len(deleted_files)}):")
        for file_path in deleted_files[:3]:  # Show first 3
            click.echo(f"      • {file_path}")
        if len(deleted_files) > 3:
            click.echo(f"      • ... and {len(deleted_files) - 3} more")


def show_validation_summary(total_tests: int, passed_tests: int, failed_tests: int,
                           success_rate: float, failed_policies: List[str] = None) -> None:
    """Show validation results summary."""
    click.echo(f"\n🔍 Validation Summary:")
    click.echo(f"   • Total tests: {total_tests}")
    click.echo(f"   • Passed: {passed_tests}")
    click.echo(f"   • Failed: {failed_tests}")
    click.echo(f"   • Success rate: {success_rate:.1f}%")
    
    if failed_policies:
        click.echo(f"   • Failed policies: {len(failed_policies)}")
        if len(failed_policies) <= 3:
            for policy in failed_policies:
                click.echo(f"     - {policy}")
        else:
            for policy in failed_policies[:3]:
                click.echo(f"     - {policy}")
            click.echo(f"     - ... and {len(failed_policies) - 3} more")


def show_next_steps(steps: List[str], title: str = "Next Steps") -> None:
    """Show formatted next steps to the user."""
    if not steps:
        return
    
    click.echo(f"\n🚀 {title}:")
    for i, step in enumerate(steps, 1):
        click.echo(f"   {i}. {step}")


def show_troubleshooting_tips(tips: List[str]) -> None:
    """Show troubleshooting tips for common issues."""
    if not tips:
        return
    
    click.echo(f"\n💡 Troubleshooting Tips:")
    for tip in tips:
        click.echo(f"   • {tip}")